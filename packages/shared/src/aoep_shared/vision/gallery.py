"""In-memory face gallery: enroll embeddings and match (1:N).

Each student is represented by a prototype = the mean of their enrolled
embeddings (more enrollments -> more robust). Matching is cosine similarity
against the prototype, restricted to an allowlist (the consented set) so an
unconsented student is never matched to an identity.

In production the embeddings come from the encrypted ``face_embeddings`` table
and never leave the configured boundary; this class is the pure matching logic
on top, which keeps it fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .engine import DEFAULT_MATCH_THRESHOLD, cosine_similarity


@dataclass
class Match:
    student_id: Optional[str]  # None => no confident match (anonymous)
    score: float
    matched: bool


class FaceGallery:
    def __init__(self, *, match_threshold: float = DEFAULT_MATCH_THRESHOLD) -> None:
        self.match_threshold = match_threshold
        self._embeddings: Dict[str, List[List[float]]] = {}

    def enroll(self, student_id: str, embedding: List[float]) -> int:
        """Add an embedding for ``student_id``; returns the new enrollment count."""
        self._embeddings.setdefault(student_id, []).append(list(embedding))
        return len(self._embeddings[student_id])

    def remove(self, student_id: str) -> None:
        self._embeddings.pop(student_id, None)

    def students(self) -> List[str]:
        return list(self._embeddings.keys())

    def count(self, student_id: str) -> int:
        return len(self._embeddings.get(student_id, []))

    def prototype(self, student_id: str) -> Optional[List[float]]:
        embs = self._embeddings.get(student_id)
        if not embs:
            return None
        dim = len(embs[0])
        proto = [0.0] * dim
        for e in embs:
            for i in range(dim):
                proto[i] += e[i]
        n = len(embs)
        return [v / n for v in proto]

    def identify(
        self,
        embedding: List[float],
        *,
        allowed_ids: Optional[Iterable[str]] = None,
        threshold: Optional[float] = None,
    ) -> Match:
        """Return the best matching student for ``embedding``.

        ``allowed_ids`` restricts candidates to the consented set. If the best
        score is below the threshold, returns a non-match (anonymous).
        """
        thr = self.match_threshold if threshold is None else threshold
        candidates = (
            self.students()
            if allowed_ids is None
            else [s for s in self.students() if s in set(allowed_ids)]
        )
        best_id: Optional[str] = None
        best_score = -1.0
        for sid in candidates:
            proto = self.prototype(sid)
            if proto is None:
                continue
            score = cosine_similarity(embedding, proto)
            if score > best_score:
                best_score = score
                best_id = sid
        if best_id is not None and best_score >= thr:
            return Match(student_id=best_id, score=best_score, matched=True)
        return Match(student_id=None, score=max(best_score, 0.0), matched=False)
