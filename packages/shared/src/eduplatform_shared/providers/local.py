"""Local-mode provider implementations.

These run on a single machine with no external/GPU/network dependencies so the
full teaching flow can be exercised in development and CI. They are functional
stubs: deterministic, dependency-free, and clearly marked. Production-grade
local backends (vLLM, Whisper/XTTS, InsightFace, self-hosted LiveKit, MinIO)
plug in behind these same interfaces.
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Sequence

from eduplatform_shared.providers.base import (
    LLMProvider,
    MediaProvider,
    ObjectStoreProvider,
    PaymentProvider,
    SpeechProvider,
    VisionProvider,
)

_EMBED_DIM = 64


def _hash_embedding(text: str, dim: int = _EMBED_DIM) -> List[float]:
    """Deterministic bag-of-words hashing embedding (no model weights needed)."""
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class LocalLLMProvider(LLMProvider):
    """Deterministic local LLM stub.

    Replace with a vLLM/Ollama client; the interface is unchanged. The stub
    produces a grounded answer by summarizing any RAG context embedded in the
    prompt, so the end-to-end teaching loop is demonstrable offline.
    """

    def complete(self, prompt: str, *, max_tokens: int = 512) -> str:
        marker = "CONTEXT:"
        question = prompt
        context = ""
        if marker in prompt:
            head, _, tail = prompt.partition(marker)
            context = tail.strip()
            question = head.replace("QUESTION:", "").strip()
        if context:
            snippet = " ".join(context.split())[:max_tokens]
            return (
                f"Great question. Based on the lesson material: {snippet} "
                f"In short, this directly addresses '{question.strip()}'."
            )
        return (
            f"Let's think about '{question.strip()}'. I'll explain it step by step "
            f"using what we covered in this lesson."
        )

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [_hash_embedding(t) for t in texts]


class LocalSpeechProvider(SpeechProvider):
    def transcribe(self, audio: bytes, *, language: str = "auto") -> str:
        return ""  # placeholder for Whisper large-v3

    def synthesize(self, text: str, *, language: str = "en", voice: str = "default") -> bytes:
        # placeholder for XTTS-v2; returns silent/empty payload locally.
        return b""


class LocalVisionProvider(VisionProvider):
    def identify(self, frame: bytes) -> List[str]:
        return []  # placeholder for InsightFace/ArcFace

    def attention(self, frame: bytes) -> float:
        return 1.0  # placeholder for MediaPipe gaze scoring


class LocalMediaProvider(MediaProvider):
    """Self-hosted LiveKit (dev). Tokens are dev placeholders."""

    def create_room(self, name: str) -> str:
        return name

    def access_token(self, room: str, identity: str) -> str:
        return f"dev-token:{room}:{identity}"


class LocalObjectStoreProvider(ObjectStoreProvider):
    """In-memory / filesystem-style object store (MinIO in compose)."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> str:
        self._store[key] = data
        return key

    def url(self, key: str) -> str:
        return f"local-object://{key}"


class LocalPaymentProvider(PaymentProvider):
    """Sandbox billing: permissive entitlements for development."""

    def can_start(self, class_type: str, language: str, features: Sequence[str]) -> bool:
        return True

    def record_usage(self, account_id: str, metric: str, quantity: int) -> None:
        return None
