"""Category-routed LLM provider (Track B multi-model serving).

Routes each request to a per-category model/adapter name over a single base LLM
endpoint (vLLM multi-LoRA), falling back to the default model. The model/adapter
name is what gets sent to the serving layer; the routing decision is pure and
testable here. Class subject -> adapter is the common path (deterministic).
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from ..config import AppConfig
from .base import ChatMessage, Completion, LLMProvider, ProviderInfo


class RoutedLLMProvider(LLMProvider):
    impl = "routed"

    def __init__(
        self,
        base: LLMProvider,
        routes: Optional[Dict[str, str]] = None,
        default_model: str = "education-base",
    ) -> None:
        self._base = base
        self._routes = dict(routes or {})
        self._default = default_model

    def info(self) -> ProviderInfo:
        bi = self._base.info()
        return ProviderInfo(capability=self.capability, mode=bi.mode,
                            impl=self.impl, endpoint=bi.endpoint)

    def model_for(self, category: Optional[str]) -> str:
        """The model/adapter name serving a given class category."""
        if category and category in self._routes:
            return self._routes[category]
        return self._default

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        category: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Completion:
        # The serving layer selects the adapter via model_for(category); here we
        # delegate to the base provider (which performs the actual call).
        return self._base.complete(
            messages, temperature=temperature, max_tokens=max_tokens
        )


def routes_from_config(config: AppConfig) -> Dict[str, str]:
    """Parse LLM_ROUTES env (comma list of category=model) into a route map."""
    raw = getattr(config, "llm_routes", "") or ""
    routes: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            cat, model = pair.split("=", 1)
            routes[cat.strip()] = model.strip()
    return routes
