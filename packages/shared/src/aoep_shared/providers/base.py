"""Abstract provider interfaces.

These are intentionally narrow: just enough surface for the orchestrator and the
services to depend on, with local/cloud implementations swapped underneath.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class ProviderInfo:
    """Identity of a concrete provider, useful for /health and logging."""

    capability: str
    mode: str
    impl: str
    endpoint: Optional[str] = None


class Provider(abc.ABC):
    """Base for all providers."""

    capability: str = "provider"

    @abc.abstractmethod
    def info(self) -> ProviderInfo:
        """Describe this provider instance."""

    def ready(self) -> bool:
        """Cheap readiness check that must not require network/GPU.

        Real implementations may override with a deeper probe behind a flag.
        """
        return True


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class Completion:
    text: str
    model: str
    usage_tokens: int = 0


class LLMProvider(Provider):
    """Open-weight base education LLM, served by us (RAG now, fine-tune later)."""

    capability = "llm"

    @abc.abstractmethod
    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Completion:
        ...


# --------------------------------------------------------------------------- #
# Speech (ASR / translation / TTS)
# --------------------------------------------------------------------------- #
@dataclass
class Transcript:
    text: str
    language: str
    confidence: float = 0.0


@dataclass
class Audio:
    # Reference to synthesized audio; in real impls this is bytes or an object
    # store key. Kept as a key here so the contract is testable without media.
    object_key: str
    language: str
    voice: str


class SpeechProvider(Provider):
    """Streaming multilingual ASR, language ID, translation, and TTS."""

    capability = "speech"

    @abc.abstractmethod
    def transcribe(self, audio_object_key: str) -> Transcript:
        ...

    @abc.abstractmethod
    def translate(self, text: str, *, source: str, target: str) -> str:
        ...

    @abc.abstractmethod
    def synthesize(self, text: str, *, language: str, voice: str) -> Audio:
        ...


# --------------------------------------------------------------------------- #
# Vision (face identity + attention) -- biometrics, boundary-sensitive
# --------------------------------------------------------------------------- #
@dataclass
class FaceObservation:
    track_id: str
    embedding_ref: Optional[str] = None  # encrypted ref, never raw biometrics
    attention_score: float = 0.0
    matched_student_id: Optional[str] = None


class VisionProvider(Provider):
    """Face recognition (identity) + attention/gaze scoring.

    Biometric processing stays inside whichever boundary is configured.
    """

    capability = "vision"

    @abc.abstractmethod
    def analyze_frame(
        self, frame_object_key: str, *, consented_student_ids: Iterable[str]
    ) -> list[FaceObservation]:
        ...


# --------------------------------------------------------------------------- #
# Media (LiveKit WebRTC backbone)
# --------------------------------------------------------------------------- #
@dataclass
class RoomToken:
    room: str
    identity: str
    token: str
    url: str


class MediaProvider(Provider):
    """Realtime media backbone (LiveKit) used as the internal media bus."""

    capability = "media"

    @abc.abstractmethod
    def issue_token(
        self, *, room: str, identity: str, can_publish: bool = True
    ) -> RoomToken:
        ...


# --------------------------------------------------------------------------- #
# Object store
# --------------------------------------------------------------------------- #
class ObjectStoreProvider(Provider):
    """S3-compatible object storage (MinIO/filesystem local, S3 cloud)."""

    capability = "object_store"

    @abc.abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        ...

    @abc.abstractmethod
    def url_for(self, key: str) -> str:
        ...


# --------------------------------------------------------------------------- #
# Payment / billing
# --------------------------------------------------------------------------- #
@dataclass
class CheckoutSession:
    session_id: str
    url: str
    provider: str


@dataclass
class Entitlements:
    plan: str
    languages: Sequence[str] = field(default_factory=tuple)
    solo_classes: bool = False
    cross_class_memory: bool = False
    recordings: bool = False


class PaymentProvider(Provider):
    """Subscriptions, credits, metered usage (Stripe cloud / sandbox local)."""

    capability = "payment"

    @abc.abstractmethod
    def create_checkout(self, *, customer_id: str, plan: str) -> CheckoutSession:
        ...
