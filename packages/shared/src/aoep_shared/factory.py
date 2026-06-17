"""Config-driven provider factory.

At startup a process builds a :class:`ProviderFactory` from its
:class:`~aoep_shared.config.AppConfig`. Each ``*_provider`` accessor returns the
local or cloud implementation according to that component's effective mode. This
is the single place where the local/cloud decision is made -- no code forks.
"""

from __future__ import annotations

from .config import AppConfig, DeployMode, load_config
from .providers.base import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    SpeechProvider,
    VisionProvider,
)
from .providers.llm import CloudLLMProvider, LocalLLMProvider
from .providers.media import CloudMediaProvider, LocalMediaProvider
from .providers.object_store import CloudObjectStore, LocalObjectStore
from .providers.payment import SandboxPaymentProvider, StripePaymentProvider
from .providers.speech import CloudSpeechProvider, LocalSpeechProvider
from .providers.vision import CloudVisionProvider, LocalVisionProvider


class ProviderFactory:
    """Builds providers lazily, caching one instance per capability."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._cache: dict[str, object] = {}

    @property
    def config(self) -> AppConfig:
        return self._config

    def _select(self, component: str, local_cls, cloud_cls):
        if component in self._cache:
            return self._cache[component]
        mode = self._config.mode_for(component)
        cls = local_cls if mode is DeployMode.LOCAL else cloud_cls
        instance = cls(self._config)
        self._cache[component] = instance
        return instance

    def llm(self) -> LLMProvider:
        return self._select("llm", LocalLLMProvider, CloudLLMProvider)

    def speech(self) -> SpeechProvider:
        return self._select("speech", LocalSpeechProvider, CloudSpeechProvider)

    def vision(self) -> VisionProvider:
        return self._select("vision", LocalVisionProvider, CloudVisionProvider)

    def media(self) -> MediaProvider:
        return self._select("media", LocalMediaProvider, CloudMediaProvider)

    def object_store(self) -> ObjectStoreProvider:
        return self._select("object_store", LocalObjectStore, CloudObjectStore)

    def payment(self) -> PaymentProvider:
        # local maps to the offline sandbox; cloud maps to Stripe.
        return self._select(
            "payment", SandboxPaymentProvider, StripePaymentProvider
        )

    def component_summary(self) -> dict[str, str]:
        """Human-readable map of component -> 'mode:impl' for /health."""
        summary: dict[str, str] = {}
        for cap, getter in (
            ("llm", self.llm),
            ("speech", self.speech),
            ("vision", self.vision),
            ("media", self.media),
            ("object_store", self.object_store),
            ("payment", self.payment),
        ):
            info = getter().info()
            summary[cap] = f"{info.mode}:{info.impl}"
        return summary


def build_factory(config: AppConfig | None = None) -> ProviderFactory:
    """Build a factory from an explicit config or from the environment."""
    return ProviderFactory(config or load_config())
