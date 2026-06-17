"""Runtime configuration.

Dual-mode contract: DEPLOY_MODE selects the default implementation family
(local vs cloud). Each provider may be overridden independently via a
per-component override env var, so a deployment can, for example, run cloud
everywhere but keep biometrics (vision) local for compliance.
"""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeployMode(str, enum.Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class Settings(BaseSettings):
    """Process-wide settings, populated from the environment.

    Per-component override fields default to ``None`` meaning "inherit the
    global ``deploy_mode``". Set them to ``local`` or ``cloud`` to override a
    single capability without forking code.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    deploy_mode: DeployMode = Field(default=DeployMode.LOCAL, alias="DEPLOY_MODE")

    # Per-component overrides (None -> inherit deploy_mode).
    llm_mode: Optional[DeployMode] = Field(default=None, alias="LLM_MODE")
    speech_mode: Optional[DeployMode] = Field(default=None, alias="SPEECH_MODE")
    vision_mode: Optional[DeployMode] = Field(default=None, alias="VISION_MODE")
    media_mode: Optional[DeployMode] = Field(default=None, alias="MEDIA_MODE")
    object_store_mode: Optional[DeployMode] = Field(
        default=None, alias="OBJECT_STORE_MODE"
    )
    payment_mode: Optional[DeployMode] = Field(default=None, alias="PAYMENT_MODE")

    # Endpoints / connection strings (used by cloud impls, harmless locally).
    llm_base_url: str = Field(default="http://localhost:8001/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="education-base", alias="LLM_MODEL")
    livekit_url: str = Field(default="ws://localhost:7880", alias="LIVEKIT_URL")
    database_url: str = Field(
        default="postgresql://edu:edu@localhost:5432/edu", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    object_store_endpoint: str = Field(
        default="http://localhost:9000", alias="OBJECT_STORE_ENDPOINT"
    )
    object_store_bucket: str = Field(default="edu-media", alias="OBJECT_STORE_BUCKET")

    @field_validator(
        "llm_mode",
        "speech_mode",
        "vision_mode",
        "media_mode",
        "object_store_mode",
        "payment_mode",
        mode="before",
    )
    @classmethod
    def _blank_override_is_none(cls, value):
        # The env contracts (config/local.env) ship blank overrides meaning
        # "inherit deploy_mode"; treat empty/whitespace strings as unset.
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    def mode_for(self, component: Optional[DeployMode]) -> DeployMode:
        """Resolve the effective mode for a component, honoring overrides."""
        return component if component is not None else self.deploy_mode


_settings: Optional[Settings] = None


def get_settings(refresh: bool = False) -> Settings:
    """Return a process-wide cached Settings instance.

    ``refresh=True`` rebuilds from the current environment (useful in tests).
    """
    global _settings
    if _settings is None or refresh:
        _settings = Settings()
    return _settings
