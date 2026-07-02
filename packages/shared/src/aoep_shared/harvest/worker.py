"""Harvest worker: license-gate -> fetch -> extract -> content-dedup -> emit.

Decoupled via callables so it is offline-testable and reusable:
- fetcher(spec)   -> raw bytes/str (real: httpx with robots/rate-limit; tests: mock)
- extractor(spec, raw) -> deck-like dict (real: curriculum.ingest; tests: simple)
- sink(record)    -> persist (real: POST /decks + catalog; tests: list.append)

Designed to run 24/7 on a separate worker agent against a HarvestQueue.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Optional, Set, Union

RawPayload = Union[str, bytes]

from .queue import HarvestQueue
from .sources import SourceSpec, is_allowed


@dataclass
class HarvestStats:
    fetched: int = 0
    ingested: int = 0
    skipped_license: int = 0
    skipped_dup: int = 0
    errors: int = 0


def _content_hash(data: str | bytes) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class HarvestWorker:
    def __init__(
        self,
        fetcher: Callable[[SourceSpec], RawPayload],
        extractor: Callable[[SourceSpec, RawPayload], dict],
        sink: Callable[[dict], None],
        *,
        allowlist: Optional[Set[str]] = None,
    ) -> None:
        self._fetch = fetcher
        self._extract = extractor
        self._sink = sink
        self._allowlist = allowlist
        self._content_seen: Set[str] = set()
        self.stats = HarvestStats()

    def process(self, spec: SourceSpec) -> str:
        """Process one source; returns a status string."""
        if not is_allowed(spec.license, allowlist=self._allowlist):
            self.stats.skipped_license += 1
            return "skipped_license"
        try:
            raw = self._fetch(spec)
            self.stats.fetched += 1
        except Exception:
            self.stats.errors += 1
            return "error"

        chash = _content_hash(raw)
        if chash in self._content_seen:
            self.stats.skipped_dup += 1
            return "skipped_dup"
        self._content_seen.add(chash)

        record = self._extract(spec, raw)
        record.setdefault("source", spec.url)
        record.setdefault("license", spec.license)
        self._sink(record)
        self.stats.ingested += 1
        return "ingested"

    def run(self, queue: HarvestQueue, *, max_items: Optional[int] = None) -> HarvestStats:
        processed = 0
        while True:
            if max_items is not None and processed >= max_items:
                break
            spec = queue.dequeue()
            if spec is None:
                break
            self.process(spec)
            processed += 1
        return self.stats
