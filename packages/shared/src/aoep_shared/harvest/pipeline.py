"""Phase 22 - quality/license gate + idempotent, batch-versioned catalog upsert.

Sits between the harvest worker (fetch/extract/normalize) and the catalog: every
candidate passes the license gate (Workstream 1/6) and an optional validation
gate (Workstream 1) before an idempotent upsert (re-harvesting the same source
updates, never duplicates). Upserts are grouped into BATCHES so a bad harvest run
is revertible in one call. Pure/offline-testable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set

from .sources import SourceSpec, is_allowed


def catalog_key(spec: SourceSpec) -> str:
    """Stable idempotency key for a source (its normalized URL)."""
    return hashlib.sha256(spec.url.strip().lower().encode("utf-8")).hexdigest()[:16]


class CatalogUpsertStore:
    """In-memory idempotent store with batch-level revert (catalog stand-in)."""

    def __init__(self) -> None:
        self.items: Dict[str, dict] = {}
        self._batches: Dict[str, Set[str]] = {}

    def upsert(self, key: str, record: dict, batch_id: str) -> bool:
        inserted = key not in self.items
        rec = {**record, "_batch": batch_id}
        self.items[key] = rec
        self._batches.setdefault(batch_id, set()).add(key)
        return inserted

    def revert_batch(self, batch_id: str) -> int:
        removed = 0
        for key in self._batches.pop(batch_id, set()):
            if self.items.get(key, {}).get("_batch") == batch_id:
                del self.items[key]
                removed += 1
        return removed


@dataclass
class BatchMetrics:
    batch_id: str
    ingested: int = 0
    upserted: int = 0          # new inserts
    updated: int = 0           # idempotent updates
    dropped_license: int = 0
    dropped_validation: int = 0


class HarvestPipeline:
    def __init__(
        self,
        store: CatalogUpsertStore,
        *,
        validator: Optional[Callable[[dict], bool]] = None,
        allowlist: Optional[Set[str]] = None,
    ) -> None:
        self.store = store
        self._validator = validator
        self._allowlist = allowlist

    def process(self, spec: SourceSpec, record: dict, batch_id: str,
                metrics: BatchMetrics) -> str:
        if not is_allowed(spec.license, allowlist=self._allowlist):
            metrics.dropped_license += 1
            return "dropped_license"
        if self._validator is not None and not self._validator(record):
            metrics.dropped_validation += 1
            return "dropped_validation"
        inserted = self.store.upsert(catalog_key(spec), record, batch_id)
        metrics.ingested += 1
        if inserted:
            metrics.upserted += 1
            return "upserted"
        metrics.updated += 1
        return "updated"

    def run_batch(self, items, batch_id: str) -> BatchMetrics:
        """items: iterable of (SourceSpec, record dict)."""
        metrics = BatchMetrics(batch_id=batch_id)
        for spec, record in items:
            self.process(spec, record, batch_id, metrics)
        return metrics
