"""Cloud-mode provider implementations.

These target managed/GPU backends (hosted vLLM/Triton, GPU speech & vision
pods, LiveKit cluster, S3-compatible storage, Stripe). Network/credentials are
not available in this dev/CI environment, so the heavy paths raise a clear
``CloudProviderUnavailable`` until wired to real endpoints. The point of these
classes is that the factory selects them by env with NO code forks; the local
implementations cover the offline development flow.
"""

from __future__ import annotations

from typing import List, Sequence

from eduplatform_shared.config import Settings
from eduplatform_shared.providers.base import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    SpeechProvider,
    VisionProvider,
)


class CloudProviderUnavailable(RuntimeError):
    """Raised when a cloud backend is selected but not reachable/configured."""


class CloudLLMProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model

    def complete(self, prompt: str, *, max_tokens: int = 512) -> str:
        raise CloudProviderUnavailable(
            f"Cloud LLM at {self.base_url} not configured in this environment."
        )

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        raise CloudProviderUnavailable(
            f"Cloud LLM embeddings at {self.base_url} not configured."
        )


class CloudSpeechProvider(SpeechProvider):
    def transcribe(self, audio: bytes, *, language: str = "auto") -> str:
        raise CloudProviderUnavailable("Cloud speech pods not configured.")

    def synthesize(self, text: str, *, language: str = "en", voice: str = "default") -> bytes:
        raise CloudProviderUnavailable("Cloud speech pods not configured.")


class CloudVisionProvider(VisionProvider):
    def identify(self, frame: bytes) -> List[str]:
        raise CloudProviderUnavailable("Cloud vision pods not configured.")

    def attention(self, frame: bytes) -> float:
        raise CloudProviderUnavailable("Cloud vision pods not configured.")


class CloudMediaProvider(MediaProvider):
    def __init__(self, settings: Settings) -> None:
        self.livekit_url = settings.livekit_url

    def create_room(self, name: str) -> str:
        raise CloudProviderUnavailable("LiveKit cloud credentials not configured.")

    def access_token(self, room: str, identity: str) -> str:
        raise CloudProviderUnavailable("LiveKit cloud credentials not configured.")


class CloudObjectStoreProvider(ObjectStoreProvider):
    def __init__(self, settings: Settings) -> None:
        self.endpoint = settings.object_store_endpoint
        self.bucket = settings.object_store_bucket

    def put(self, key: str, data: bytes) -> str:
        raise CloudProviderUnavailable("S3-compatible store not configured.")

    def url(self, key: str) -> str:
        return f"https://{self.bucket}.s3/{key}"


class CloudPaymentProvider(PaymentProvider):
    """Stripe-backed entitlements (cloud)."""

    def can_start(self, class_type: str, language: str, features: Sequence[str]) -> bool:
        raise CloudProviderUnavailable("Stripe billing not configured.")

    def record_usage(self, account_id: str, metric: str, quantity: int) -> None:
        raise CloudProviderUnavailable("Stripe billing not configured.")
