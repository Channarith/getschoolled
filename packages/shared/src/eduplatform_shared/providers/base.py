"""Abstract provider interfaces.

These are intentionally narrow so that local and cloud implementations stay
swappable. Implementations live in ``local.py`` and ``cloud.py``.
"""

from __future__ import annotations

import abc
from typing import List, Sequence


class LLMProvider(abc.ABC):
    """Text generation for the teaching agents."""

    name: str = "llm"

    @abc.abstractmethod
    def complete(self, prompt: str, *, max_tokens: int = 512) -> str:
        """Return a completion for ``prompt``."""

    @abc.abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return an embedding vector per input text (used for RAG)."""


class SpeechProvider(abc.ABC):
    """Streaming ASR + translation + TTS gateway."""

    name: str = "speech"

    @abc.abstractmethod
    def transcribe(self, audio: bytes, *, language: str = "auto") -> str: ...

    @abc.abstractmethod
    def synthesize(self, text: str, *, language: str = "en", voice: str = "default") -> bytes: ...


class VisionProvider(abc.ABC):
    """Face recognition + attention scoring (biometrics, consent-gated)."""

    name: str = "vision"

    @abc.abstractmethod
    def identify(self, frame: bytes) -> List[str]: ...

    @abc.abstractmethod
    def attention(self, frame: bytes) -> float: ...


class MediaProvider(abc.ABC):
    """Real-time media backbone (LiveKit) access tokens / rooms."""

    name: str = "media"

    @abc.abstractmethod
    def create_room(self, name: str) -> str: ...

    @abc.abstractmethod
    def access_token(self, room: str, identity: str) -> str: ...


class ObjectStoreProvider(abc.ABC):
    """Blob storage for slides, media and recordings."""

    name: str = "object_store"

    @abc.abstractmethod
    def put(self, key: str, data: bytes) -> str: ...

    @abc.abstractmethod
    def url(self, key: str) -> str: ...


class PaymentProvider(abc.ABC):
    """Billing / entitlement backend."""

    name: str = "payment"

    @abc.abstractmethod
    def can_start(self, class_type: str, language: str, features: Sequence[str]) -> bool: ...

    @abc.abstractmethod
    def record_usage(self, account_id: str, metric: str, quantity: int) -> None: ...
