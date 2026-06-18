"""Phase 23 - run-at-scale harvest loop with checkpoint/resume.

Ties the queue + worker fetch/extract + the gate/upsert pipeline into one
resumable loop suitable for a long-running worker. The Checkpoint persists which
sources are already done so a restarted worker skips them (idempotent + safe to
stop/restart), which is what makes the 24/7 100k+ crawl tractable. Pure/offline-
testable (inject MockFetcher + a simple extractor).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Set

from .pipeline import BatchMetrics, HarvestPipeline, catalog_key
from .queue import HarvestQueue
from .sources import SourceSpec


@dataclass
class Checkpoint:
    path: Optional[str] = None
    done: Set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Optional[str]) -> "Checkpoint":
        if path and Path(path).is_file():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(path=path, done=set(data.get("done", [])))
        return cls(path=path, done=set())

    def is_done(self, key: str) -> bool:
        return key in self.done

    def mark_done(self, key: str) -> None:
        self.done.add(key)

    def save(self) -> None:
        if not self.path:
            return
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"done": sorted(self.done)}), encoding="utf-8")


def harvest_loop(
    queue: HarvestQueue,
    pipeline: HarvestPipeline,
    *,
    fetcher: Callable[[SourceSpec], str],
    extractor: Callable[[SourceSpec, str], dict],
    batch_id: str,
    checkpoint: Optional[Checkpoint] = None,
    max_items: Optional[int] = None,
) -> BatchMetrics:
    cp = checkpoint or Checkpoint()
    metrics = BatchMetrics(batch_id=batch_id)
    processed = 0
    while True:
        if max_items is not None and processed >= max_items:
            break
        spec = queue.dequeue()
        if spec is None:
            break
        key = catalog_key(spec)
        if cp.is_done(key):
            continue  # resume: already ingested in a prior run
        try:
            raw = fetcher(spec)
            record = extractor(spec, raw)
        except Exception:
            processed += 1
            continue
        pipeline.process(spec, record, batch_id, metrics)
        cp.mark_done(key)
        cp.save()
        processed += 1
    return metrics
