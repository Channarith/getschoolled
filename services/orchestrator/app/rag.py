"""Minimal RAG retriever.

Embeds lesson passages with the configured LLMProvider and retrieves the most
relevant ones for a question via cosine similarity. Works offline with the
local hashing embedder; swaps to real embeddings in cloud mode with no change
to callers.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from eduplatform_shared.providers.base import LLMProvider


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class RagIndex:
    def __init__(self, llm: LLMProvider, passages: List[str]) -> None:
        self.llm = llm
        self.passages = passages
        self.vectors = llm.embed(passages) if passages else []

    def retrieve(self, query: str, k: int = 2) -> List[str]:
        if not self.passages:
            return []
        qv = self.llm.embed([query])[0]
        scored = sorted(
            zip(self.passages, self.vectors),
            key=lambda pv: _cosine(qv, pv[1]),
            reverse=True,
        )
        return [p for p, _ in scored[:k]]
