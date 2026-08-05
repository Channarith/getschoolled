"""Environment-driven config for the webcam-recognition lab.

Everything is selected by env so the same code runs offline (no key, deterministic
agent fallback) or against the real xAI API -- no code forks, matching the wider
platform convention.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class LabConfig:
    """Resolved configuration for a running lab process."""

    # --- xAI (Grok) voice agent -------------------------------------------- #
    # When ``xai_api_key`` is set the agent calls the real OpenAI-compatible xAI
    # endpoint; otherwise it uses the built-in deterministic fallback so the
    # teaching loop always responds.
    xai_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    xai_model: str = "grok-2-latest"
    xai_timeout_s: float = 30.0
    # Persona the agent speaks as (the platform's AI teacher).
    agent_name: str = "Theodore"

    # --- presence / absence tuning ----------------------------------------- #
    # A learner must be unseen for this long before we declare them AWAY, and
    # seen again for this long before we declare them back -- debouncing avoids
    # flicker from a single dropped frame or a quick glance away.
    absent_grace_s: float = 4.0
    present_grace_s: float = 1.0

    # --- silhouette detection ---------------------------------------------- #
    # Fraction of the frame a person box must cover to count as "present" (guards
    # against tiny spurious detections in the background).
    min_silhouette_coverage: float = 0.03
    # HOG detector hit threshold; higher => fewer false positives.
    hog_hit_threshold: float = 0.0

    def with_overrides(self, **kw: object) -> "LabConfig":
        from dataclasses import replace

        return replace(self, **kw)  # type: ignore[arg-type]


def _get(src: Mapping[str, str], key: str, default: str) -> str:
    value = src.get(key)
    return default if value is None or value.strip() == "" else value.strip()


def load_lab_config(env: Optional[Mapping[str, str]] = None) -> LabConfig:
    """Build a :class:`LabConfig` from an environment mapping (defaults: os.environ)."""
    src: Mapping[str, str] = os.environ if env is None else env
    return LabConfig(
        xai_api_key=_get(src, "XAI_API_KEY", ""),
        xai_base_url=_get(src, "XAI_BASE_URL", "https://api.x.ai/v1"),
        xai_model=_get(src, "XAI_MODEL", "grok-2-latest"),
        xai_timeout_s=float(_get(src, "XAI_TIMEOUT_S", "30.0")),
        agent_name=_get(src, "AGENT_NAME", "Theodore"),
        absent_grace_s=float(_get(src, "ABSENT_GRACE_S", "4.0")),
        present_grace_s=float(_get(src, "PRESENT_GRACE_S", "1.0")),
        min_silhouette_coverage=float(_get(src, "MIN_SILHOUETTE_COVERAGE", "0.03")),
        hog_hit_threshold=float(_get(src, "HOG_HIT_THRESHOLD", "0.0")),
    )
