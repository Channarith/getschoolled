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
    # Engagement signals (machine vision) used to adapt teaching in real time.
    gaze_frontal: float = 0.0
    # ``None`` where emotion recognition is prohibited by region (EU AI Act).
    expression: Optional[str] = "unknown"


@dataclass
class EmbeddedFace:
    """A face already detected + embedded by an on-device (client/edge) pipeline.

    The hybrid path lets the camera-bearing device run YuNet+SFace locally and
    send only the resulting 128-d embedding (plus the 5 landmarks/bbox needed for
    engagement) to the server. The raw frame never leaves the device; the server
    only matches the embedding against the consented gallery and enforces the
    region/consent compliance gates.
    """

    embedding: Sequence[float]
    # YuNet's 5 landmarks (right_eye, left_eye, nose, right_mouth, left_mouth)
    # plus the bbox + frame_size let the server derive attention/gaze without the
    # pixels. Empty/None => identity-only (no engagement signals).
    landmarks: Sequence[tuple[float, float]] = ()
    bbox: Optional[tuple[int, int, int, int]] = None
    frame_size: Optional[tuple[int, int]] = None


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

    # --- hybrid (on-device embedding) path --------------------------------- #
    # These accept embeddings computed by the client/edge device so the server
    # never sees the raw frame and never needs to load/run the model itself.
    def analyze_embedding(
        self,
        faces: Sequence["EmbeddedFace"],
        *,
        consented_student_ids: Iterable[str],
    ) -> list[FaceObservation]:
        raise NotImplementedError

    def enroll_embedding(self, student_id: str, embedding: Sequence[float]) -> int:
        raise NotImplementedError


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
    method: str = "card"
    # For manual methods (e.g. Zelle) there is no hosted page; instructions
    # tell the payer how to complete the transfer.
    instructions: str = ""


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

    def supported_methods(self) -> "frozenset":
        """Payment methods this provider can actually process."""
        return frozenset()

    def supports(self, method) -> bool:
        return method in self.supported_methods()

    @abc.abstractmethod
    def create_checkout(
        self, *, customer_id: str, plan: str, method=None
    ) -> CheckoutSession:
        ...


# --------------------------------------------------------------------------- #
# Search (course validation via web corroboration)
# --------------------------------------------------------------------------- #
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str


class SearchProvider(Provider):
    """A web search engine adapter used for course validation.

    Each concrete engine (Bing, Google CSE, Brave, Kagi, Baidu, ...) is enabled
    only when its API key is configured (``ready()``); a deterministic mock
    powers offline tests and no-key runs.
    """

    capability = "search"
    engine: str = "search"

    def ready(self) -> bool:  # pragma: no cover - overridden per adapter
        return True

    @abc.abstractmethod
    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        ...


# --------------------------------------------------------------------------- #
# OCR (homework scanning: typed + handwritten)
# --------------------------------------------------------------------------- #
@dataclass
class OcrResult:
    text: str
    handwritten: bool = False
    confidence: float = 1.0
    blocks: Sequence[str] = ()


class OcrProvider(Provider):
    """Reads text from a scanned homework image/PDF (typed or handwritten)."""

    capability = "ocr"

    @abc.abstractmethod
    def read(self, content: bytes, *, hint: Optional[str] = None) -> OcrResult:
        ...


# --------------------------------------------------------------------------- #
# Embodiment (drive a screen avatar today, a humanoid robot later)
# --------------------------------------------------------------------------- #
@dataclass
class EmbodimentAction:
    modality: str           # "speech" | "gesture" | "display"
    payload: dict


class EmbodimentProvider(Provider):
    """Renders teaching actions onto a body: a screen avatar (today) or a
    humanoid robot's speakers/actuators/cameras (later). The same Teaching
    Director brain drives either, so porting to a robot is a provider swap."""

    capability = "embodiment"

    @abc.abstractmethod
    def say(self, text: str, *, language: str = "en") -> EmbodimentAction:
        ...

    @abc.abstractmethod
    def gesture(self, name: str) -> EmbodimentAction:
        ...

    def perceive(self) -> dict:
        """Latest sensory snapshot (camera/audio). Empty when not embodied."""
        return {}
