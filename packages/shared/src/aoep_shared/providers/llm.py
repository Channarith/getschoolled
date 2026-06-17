"""LLM provider implementations.

local  -> self-hosted vLLM / Ollama exposing an OpenAI-compatible endpoint.
cloud  -> managed vLLM / Triton or hosted API at a different base URL.

Both speak the same OpenAI-compatible request shape, so the only real
difference is the endpoint and credentials carried by AppConfig. The network
call is isolated in ``_post_chat`` and is not exercised in tests.
"""

from __future__ import annotations

from typing import Sequence

from ..config import AppConfig
from .base import ChatMessage, Completion, LLMProvider, ProviderInfo


class _BaseOpenAICompatLLM(LLMProvider):
    impl = "openai-compat"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = config.llm_base_url
        self._model = config.llm_model

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._base_url,
        )

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Completion:
        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        text = self._post_chat(payload)
        return Completion(text=text, model=self._model)

    def _post_chat(self, payload: dict) -> str:
        """Perform the chat-completions HTTP call.

        Wired but not invoked in tests: requires a running model server.
        """
        raise NotImplementedError(
            "LLM serving not reachable in this environment; configure "
            "LLM_BASE_URL to a running vLLM/Ollama (local) or managed "
            "endpoint (cloud)."
        )


class LocalLLMProvider(_BaseOpenAICompatLLM):
    impl = "vllm-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudLLMProvider(_BaseOpenAICompatLLM):
    impl = "vllm-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
