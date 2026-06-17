"""Config-driven provider factory.

Selects the local or cloud implementation for each capability based on
:class:`~eduplatform_shared.config.Settings`. The global ``deploy_mode`` sets
the default; per-component overrides (e.g. ``VISION_MODE=local`` while
``DEPLOY_MODE=cloud``) let a single capability differ without code forks.
"""

from __future__ import annotations

from typing import Optional

from eduplatform_shared.config import DeployMode, Settings, get_settings
from eduplatform_shared.providers import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    SpeechProvider,
    VisionProvider,
)
from eduplatform_shared.providers import cloud as _cloud
from eduplatform_shared.providers import local as _local


class ProviderFactory:
    """Builds providers for the effective deployment mode."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _mode(self, override) -> DeployMode:
        return self.settings.mode_for(override)

    def llm(self) -> LLMProvider:
        if self._mode(self.settings.llm_mode) is DeployMode.CLOUD:
            return _cloud.CloudLLMProvider(self.settings)
        return _local.LocalLLMProvider()

    def speech(self) -> SpeechProvider:
        if self._mode(self.settings.speech_mode) is DeployMode.CLOUD:
            return _cloud.CloudSpeechProvider()
        return _local.LocalSpeechProvider()

    def vision(self) -> VisionProvider:
        if self._mode(self.settings.vision_mode) is DeployMode.CLOUD:
            return _cloud.CloudVisionProvider()
        return _local.LocalVisionProvider()

    def media(self) -> MediaProvider:
        if self._mode(self.settings.media_mode) is DeployMode.CLOUD:
            return _cloud.CloudMediaProvider(self.settings)
        return _local.LocalMediaProvider()

    def object_store(self) -> ObjectStoreProvider:
        if self._mode(self.settings.object_store_mode) is DeployMode.CLOUD:
            return _cloud.CloudObjectStoreProvider(self.settings)
        return _local.LocalObjectStoreProvider()

    def payment(self) -> PaymentProvider:
        if self._mode(self.settings.payment_mode) is DeployMode.CLOUD:
            return _cloud.CloudPaymentProvider()
        return _local.LocalPaymentProvider()


_factory: Optional[ProviderFactory] = None


def get_provider_factory(refresh: bool = False) -> ProviderFactory:
    """Return a process-wide cached factory."""
    global _factory
    if _factory is None or refresh:
        _factory = ProviderFactory(get_settings(refresh=refresh))
    return _factory
