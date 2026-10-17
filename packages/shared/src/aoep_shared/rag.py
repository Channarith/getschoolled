"""Lexical RAG index over sample-curriculum/.

Ranking is Okapi BM25 on content words. English function words are dropped
from the query and the document so a short file cannot win on "what" or "is".
Scores are scaled into (0, 1), so a caller minimum still means real overlap.

A hashed dense vector and passage chunking were measured on the golden set.
The dense mix was slower and did not raise quality. Chunking picked up one
extra lexical hit on a different sense of "gravity" and is not the default.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    """
    a an the of to and or in on for with from by at as is are was were be been
    being it this that these those into over under about what how do does did
    why who which when where can could should would will just than then not no
    nor you your we our they their i my me he she his her them us
    """.split()
)
_BM25_K1 = 1.2
_BM25_B = 0.75
_BM25_NORM = 4.0


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def rewrite_query(text: str) -> list[str]:
    """Content words only, in order, duplicates removed.

    This is the query rewrite the ranker uses. It does not add synonyms.
    """
    seen: set[str] = set()
    out: list[str] = []
    for token in _tokenize(text):
        if token in _STOP or len(token) <= 1 or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _content_counts(text: str) -> Counter[str]:
    return Counter(token for token in _tokenize(text) if token not in _STOP and len(token) > 1)


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    tokens: frozenset[str] = frozenset()

    @classmethod
    def from_text(cls, doc_id: str, title: str, text: str) -> "Document":
        counts = _content_counts(f"{title}\n{text}")
        return cls(doc_id=doc_id, title=title, text=text, tokens=frozenset(counts))


@dataclass
class Retrieved:
    document: Document
    score: float


class RagIndex:
    """An in-memory BM25 index over curriculum documents."""

    def __init__(self, documents: Iterable[Document] | None = None) -> None:
        self._docs: list[Document] = []
        self._stats: list[tuple[Counter[str], int]] = []
        self._df: Counter[str] = Counter()
        self._avgdl = 1.0
        self._dirty = True
        for document in documents or []:
            self.add(document)

    def __len__(self) -> int:
        return len(self._docs)

    def add(self, document: Document) -> None:
        if not document.tokens:
            document.tokens = frozenset(
                _content_counts(f"{document.title}\n{document.text}")
            )
        self._docs.append(document)
        self._dirty = True

    def _prepare(self) -> None:
        if not self._dirty:
            return
        stats: list[tuple[Counter[str], int]] = []
        df: Counter[str] = Counter()
        for doc in self._docs:
            tf = _content_counts(f"{doc.title}\n{doc.text}")
            for token in _content_counts(doc.title):
                tf[token] += 2
            length = sum(tf.values()) or 1
            stats.append((tf, length))
            for token in tf:
                df[token] += 1
        total = sum(length for _, length in stats)
        self._stats = stats
        self._df = df
        self._avgdl = (total / len(stats)) if stats else 1.0
        self._dirty = False

    def retrieve(self, query: str, *, top_k: int = 3) -> list[Retrieved]:
        terms = rewrite_query(query)
        if not terms or top_k <= 0:
            return []
        self._prepare()
        n_docs = len(self._docs) or 1
        avgdl = self._avgdl or 1.0
        scored: list[Retrieved] = []
        for doc, (tf, length) in zip(self._docs, self._stats):
            raw = 0.0
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = freq + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * length / avgdl)
                raw += idf * (freq * (_BM25_K1 + 1.0)) / denom
            if raw <= 0.0:
                continue
            scored.append(Retrieved(document=doc, score=raw / (raw + _BM25_NORM)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    @classmethod
    def from_directory(cls, root: str | Path, *, pattern: str = "*.txt") -> "RagIndex":
        """Load every matching text file under ``root`` as one document."""
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
        index._prepare()
        return index
