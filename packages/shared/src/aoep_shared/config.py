"""Dual-mode configuration for AOEP.

The exact same code runs either fully local (single machine / docker compose) or
against a cloud backend (Kubernetes + GPU pool). The mode is selected purely by
environment / config -- there are no code forks.

DEPLOY_MODE sets the default for every heavy capability. Each capability can be
overridden independently (e.g. run the LLM in the cloud while keeping biometrics
local for compliance) via a per-component ``*_MODE`` variable.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Mapping, MutableMapping, Optional

from pydantic import BaseModel, Field


class DeployMode(str, Enum):
    """Top-level deployment target."""

    LOCAL = "local"
    CLOUD = "cloud"


# A per-component mode is the same value space as the deploy mode; keeping a
# distinct alias documents intent at call sites and leaves room to diverge.
ComponentMode = DeployMode


# Components whose implementation is chosen by mode. The biometrics-bearing
# components (vision/media) can be pinned locally regardless of DEPLOY_MODE to
# keep face data inside a configured boundary (a key compliance lever).
COMPONENTS = (
    "llm",
    "speech",
    "vision",
    "media",
    "object_store",
    "payment",
    "database",
    "bus",
)


def _coerce_mode(value: Optional[str], default: DeployMode) -> DeployMode:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    try:
        return DeployMode(normalized)
    except ValueError as exc:  # pragma: no cover - defensive
        valid = ", ".join(m.value for m in DeployMode)
        raise ValueError(
            f"Invalid mode {value!r}; expected one of: {valid}"
        ) from exc


class AppConfig(BaseModel):
    """Resolved configuration for a running process.

    ``deploy_mode`` is the default; ``component_modes`` holds the effective mode
    for every component after applying per-component overrides.
    """

    deploy_mode: DeployMode = DeployMode.LOCAL
    component_modes: dict[str, DeployMode] = Field(default_factory=dict)

    # Endpoints / connection strings consumed by provider implementations. These
    # are intentionally generic strings so the same config object serves both
    # local container URLs and cloud service URLs.
    llm_base_url: str = "http://llm:8000/v1"
    llm_model: str = "aoep-base-edu"
    # Track B routing: "category=model,category=model" -> per-domain adapters.
    llm_routes: str = ""
    speech_base_url: str = "http://speech:8100"
    vision_base_url: str = "http://perception:8200"
    # Face-model cache dir (empty -> ~/.cache/aoep/models) and cosine match
    # threshold for SFace embeddings (0.363 is OpenCV's calibrated default).
    vision_model_dir: str = ""
    vision_match_threshold: float = 0.363
    # Persisted face gallery (cross-session student memory). Empty => in-memory.
    vision_gallery_path: str = ""
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret"
    object_store_endpoint: str = "http://minio:9000"
    object_store_bucket: str = "aoep"
    object_store_access_key: str = "aoep"
    object_store_secret_key: str = "aoep-secret"
    database_url: str = "postgresql://aoep:aoep@postgres:5432/aoep"
    redis_url: str = "redis://redis:6379/0"
    payment_api_key: str = ""
    # Course-validation search engines (each enabled only when its key is set).
    bing_search_key: str = ""
    google_cse_key: str = ""
    google_cse_cx: str = ""
    brave_search_key: str = ""
    kagi_api_key: str = ""
    baidu_api_key: str = ""

    def mode_for(self, component: str) -> DeployMode:
        """Return the effective mode for ``component``."""
        if component not in COMPONENTS:
            raise KeyError(f"Unknown component {component!r}")
        return self.component_modes.get(component, self.deploy_mode)

    def is_local(self, component: str) -> bool:
        return self.mode_for(component) is DeployMode.LOCAL

    def is_cloud(self, component: str) -> bool:
        return self.mode_for(component) is DeployMode.CLOUD


def load_config(
    env: Optional[Mapping[str, str]] = None,
) -> AppConfig:
    """Build an :class:`AppConfig` from an environment mapping.

    Resolution order for each component's mode:
      1. ``<COMPONENT>_MODE`` (e.g. ``LLM_MODE``) if set.
      2. ``DEPLOY_MODE`` otherwise.
      3. ``local`` if nothing is set.
    """

    source: Mapping[str, str] = os.environ if env is None else env

    deploy_mode = _coerce_mode(source.get("DEPLOY_MODE"), DeployMode.LOCAL)

    component_modes: MutableMapping[str, DeployMode] = {}
    for component in COMPONENTS:
        override = source.get(f"{component.upper()}_MODE")
        component_modes[component] = _coerce_mode(override, deploy_mode)

    def get(key: str, default: str) -> str:
        value = source.get(key)
        return default if value is None or value == "" else value

    return AppConfig(
        deploy_mode=deploy_mode,
        component_modes=dict(component_modes),
        llm_base_url=get("LLM_BASE_URL", "http://llm:8000/v1"),
        llm_model=get("LLM_MODEL", "aoep-base-edu"),
        llm_routes=get("LLM_ROUTES", ""),
        speech_base_url=get("SPEECH_BASE_URL", "http://speech:8100"),
        vision_base_url=get("VISION_BASE_URL", "http://perception:8200"),
        vision_model_dir=get("VISION_MODEL_DIR", ""),
        vision_match_threshold=float(get("VISION_MATCH_THRESHOLD", "0.363")),
        vision_gallery_path=get("VISION_GALLERY_PATH", ""),
        livekit_url=get("LIVEKIT_URL", "ws://livekit:7880"),
        livekit_api_key=get("LIVEKIT_API_KEY", "devkey"),
        livekit_api_secret=get("LIVEKIT_API_SECRET", "devsecret"),
        object_store_endpoint=get("OBJECT_STORE_ENDPOINT", "http://minio:9000"),
        object_store_bucket=get("OBJECT_STORE_BUCKET", "aoep"),
        object_store_access_key=get("OBJECT_STORE_ACCESS_KEY", "aoep"),
        object_store_secret_key=get("OBJECT_STORE_SECRET_KEY", "aoep-secret"),
        database_url=get(
            "DATABASE_URL", "postgresql://aoep:aoep@postgres:5432/aoep"
        ),
        redis_url=get("REDIS_URL", "redis://redis:6379/0"),
        payment_api_key=get("PAYMENT_API_KEY", ""),
        bing_search_key=get("BING_SEARCH_KEY", ""),
        google_cse_key=get("GOOGLE_CSE_KEY", ""),
        google_cse_cx=get("GOOGLE_CSE_CX", ""),
        brave_search_key=get("BRAVE_SEARCH_KEY", ""),
        kagi_api_key=get("KAGI_API_KEY", ""),
        baidu_api_key=get("BAIDU_API_KEY", ""),
    )
