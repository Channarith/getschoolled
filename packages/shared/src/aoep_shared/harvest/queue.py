"""Durable-ish in-memory harvest queue with URL dedup.

The production worker backs this with Redis/DB; the interface (enqueue/dequeue +
seen-set dedup) is identical so the worker logic is unchanged and testable here.
"""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Deque, Iterable, Optional, Set

from .sources import SourceSpec


def url_key(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()[:16]


class HarvestQueue:
    def __init__(self) -> None:
        self._q: Deque[SourceSpec] = deque()
        self._seen: Set[str] = set()

    def enqueue(self, spec: SourceSpec) -> bool:
        """Add a source; returns False if its URL was already queued/seen."""
        key = url_key(spec.url)
        if key in self._seen:
            return False
        self._seen.add(key)
        self._q.append(spec)
        return True

    def enqueue_many(self, specs: Iterable[SourceSpec]) -> int:
        return sum(1 for s in specs if self.enqueue(s))

    def dequeue(self) -> Optional[SourceSpec]:
        return self._q.popleft() if self._q else None

    def __len__(self) -> int:
        return len(self._q)
