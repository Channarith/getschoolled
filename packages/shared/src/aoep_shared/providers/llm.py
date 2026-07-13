"""LLM provider implementations (OpenAI-compatible chat completions).

local     -> self-hosted vLLM / Ollama exposing an OpenAI-compatible endpoint.
cloud     -> managed vLLM / Triton at a different base URL.
nemotron  -> NVIDIA Nemotron via NIM (build.nvidia.com / integrate.api.nvidia.com)
             or a self-hosted vLLM serving a Nemotron model. Same OpenAI-compatible
             wire format; used for real-time conversational agents (with STREAMING
             for low-latency voice answers).

The HTTP call is isolated in ``_transport`` (stdlib urllib) so tests can mock it
without a running model server. Both blocking ``complete`` and streaming
``complete_stream`` (SSE ``data:`` deltas) are supported.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterable, Iterator, Optional, Sequence

from ..config import AppConfig
from .base import ChatMessage, Completion, LLMProvider, ProviderInfo


class LLMError(RuntimeError):
    """Raised when the LLM endpoint call fails."""


class _BaseOpenAICompatLLM(LLMProvider):
    impl = "openai-compat"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = (config.llm_base_url or "").rstrip("/")
        self._model = config.llm_model
        self._api_key = getattr(config, "llm_api_key", "") or ""
        self._timeout = 60.0

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._base_url,
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if (self._api_key or "").strip():
            h["Authorization"] = f"Bearer {self._api_key.strip()}"
        return h

    def _payload(self, messages: Sequence[ChatMessage], *, temperature: float,
                 max_tokens: int, stream: bool) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Completion:
        payload = self._payload(messages, temperature=temperature, max_tokens=max_tokens, stream=False)
        raw = self._transport(payload, stream=False)
        text = _extract_message(raw)
        return Completion(text=text, model=self._model)

    def complete_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Iterable[str]:
        payload = self._payload(messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        for line in self._transport(payload, stream=True):
            delta = _extract_delta(line)
            if delta:
                yield delta

    # --- transport (isolated for tests) ------------------------------------ #
    def _transport(self, payload: dict, *, stream: bool):
        """POST to {base}/chat/completions. Returns a dict (blocking) or an
        iterator of SSE ``data:`` payload strings (streaming)."""
        if not self._base_url:
            raise LLMError("LLM_BASE_URL is not configured")
        url = f"{self._base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise LLMError(f"LLM HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM unreachable: {exc.reason}") from exc
        if not stream:
            body = resp.read()
            return json.loads(body.decode("utf-8"))
        return _iter_sse(resp)


def _iter_sse(resp) -> Iterator[str]:
    """Yield the JSON payload string after each ``data:`` SSE line (skips [DONE])."""
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        chunk = line[len("data:"):].strip()
        if chunk == "[DONE]":
            break
        yield chunk


def _extract_message(raw: dict) -> str:
    try:
        return (raw["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _extract_delta(chunk: str) -> str:
    """Pull the incremental content from one streamed chat.completion.chunk."""
    try:
        obj = json.loads(chunk)
        choice = obj["choices"][0]
        return choice.get("delta", {}).get("content") or ""
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return ""


class LocalLLMProvider(_BaseOpenAICompatLLM):
    impl = "vllm-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudLLMProvider(_BaseOpenAICompatLLM):
    impl = "vllm-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")


class NemotronLLMProvider(_BaseOpenAICompatLLM):
    """NVIDIA Nemotron conversational agent (OpenAI-compatible via NIM or vLLM).

    Defaults to NVIDIA's hosted NIM endpoint; override NEMOTRON_BASE_URL to point
    at a self-hosted vLLM serving a Nemotron model. Streaming is used for the
    real-time voice assistant so TTS can start on the first tokens.
    """

    impl = "nemotron"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
        self._base_url = (getattr(config, "nemotron_base_url", "")
                          or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self._model = getattr(config, "nemotron_model", "") or "nvidia/llama-3.1-nemotron-70b-instruct"
        self._api_key = (getattr(config, "nemotron_api_key", "")
                         or getattr(config, "llm_api_key", "") or "")


def nemotron_configured(config: AppConfig) -> bool:
    """True when a Nemotron agent should be used (explicit key or provider switch)."""
    if (getattr(config, "nemotron_api_key", "") or "").strip():
        return True
    return (getattr(config, "llm_provider", "") or "").strip().lower() == "nemotron"
