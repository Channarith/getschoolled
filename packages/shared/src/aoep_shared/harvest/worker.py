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

from .queue import HarvestQueue
from .errors import HarvestConfigError
from .sources import SourceSpec, spec_allowed

RawPayload = Union[str, bytes]


@dataclass
class HarvestStats:
    fetched: int = 0
    ingested: int = 0
    skipped_license: int = 0
    diverted_research: int = 0
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
        allow_unverified: bool = False,
    ) -> None:
        self._fetch = fetcher
        self._extract = extractor
        self._sink = sink
        self._allowlist = allowlist
        # The online crawler lets sources with no declared license through the pre-fetch
        # gate because it reads the page's own license before ingesting. Offline callers do not.
        self._allow_unverified = allow_unverified
        self._content_seen: Set[str] = set()
        self.stats = HarvestStats()

    def process(self, spec: SourceSpec) -> str:
        """Process one source; returns a status string."""
        if not spec_allowed(spec, allowlist=self._allowlist, allow_unverified=self._allow_unverified):
            self.stats.skipped_license += 1
            return "skipped_license"
        try:
            raw = self._fetch(spec)
            self.stats.fetched += 1
        except HarvestConfigError:
            raise  # a crawler without a contact User-Agent must stop, not count as an error
        except PermissionError:
            # robots.txt, denylist, login wall or paywall: a policy skip, not a failure.
            self.stats.skipped_license += 1
            return "skipped_license"
        except Exception:
            self.stats.errors += 1
            return "error"

        chash = _content_hash(raw)
        if chash in self._content_seen:
            self.stats.skipped_dup += 1
            return "skipped_dup"
        self._content_seen.add(chash)

        record = self._extract(spec, raw)
        if record.get("status") == "diverted_research":
            self.stats.diverted_research += 1      # kept in the research corpus, not the product
            return "diverted_research"
        if str(record.get("status", "")).startswith("rejected_"):
            # The page's own license/robots/paywall check refused it after the fetch.
            self.stats.skipped_license += 1
            return "skipped_license"
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
