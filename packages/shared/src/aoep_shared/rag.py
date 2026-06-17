"""Dependency-free RAG skeleton over sample-curriculum/.

This is the retrieval scaffold the Tutor/Q&A agent uses: it loads plain-text
lesson chunks from a curriculum directory and ranks them against a query. The
ranking here is a transparent lexical (bag-of-words overlap) scorer so it runs
with zero dependencies and is fully testable offline.

In local/cloud deployments this is swapped for pgvector similarity over
embeddings produced by the speech/LLM stack, behind the same retrieve() shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    tokens: frozenset[str] = frozenset()

    @classmethod
    def from_text(cls, doc_id: str, title: str, text: str) -> "Document":
        return cls(doc_id=doc_id, title=title, text=text, tokens=frozenset(_tokenize(text)))


@dataclass
class Retrieved:
    document: Document
    score: float


class RagIndex:
    """An in-memory lexical index over curriculum documents."""

    def __init__(self, documents: Iterable[Document] | None = None) -> None:
        self._docs: list[Document] = list(documents or [])

    def __len__(self) -> int:
        return len(self._docs)

    def add(self, document: Document) -> None:
        self._docs.append(document)

    def retrieve(self, query: str, *, top_k: int = 3) -> list[Retrieved]:
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []
        scored: list[Retrieved] = []
        for doc in self._docs:
            if not doc.tokens:
                continue
            overlap = len(q_tokens & doc.tokens)
            if overlap == 0:
                continue
            # Jaccard-like score keeps results comparable across doc sizes.
            score = overlap / len(q_tokens | doc.tokens)
            scored.append(Retrieved(document=doc, score=score))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    @classmethod
    def from_directory(cls, root: str | Path, *, pattern: str = "*.txt") -> "RagIndex":
        """Load every matching text file under ``root`` as a document."""
        root_path = Path(root)
        index = cls()
        if not root_path.exists():
            return index
        for path in sorted(root_path.rglob(pattern)):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            title = text.splitlines()[0].strip() if text.strip() else path.stem
            doc_id = str(path.relative_to(root_path))
            index.add(Document.from_text(doc_id, title, text))
        return index
