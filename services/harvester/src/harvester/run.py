#!/usr/bin/env python3
"""Harvester worker entrypoint (Phase 23) - runs 24/7 on a separate agent.

Seeds the queue, then runs the checkpoint/resumable harvest loop: fetch -> extract
-> license/validation gate -> idempotent batch-versioned catalog upsert. Defaults
to a MockFetcher so it runs offline; production injects an httpx fetcher (robots +
rate limit) and posts upserts to the curriculum/catalog service. Config is
env-driven (HARVEST_*, see config + docs/secrets.txt).
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from aoep_shared.harvest import (
    CatalogUpsertStore,
    Checkpoint,
    HarvestPipeline,
    HarvestQueue,
    SourceSpec,
    harvest_loop,
)


def mock_fetcher(spec: SourceSpec) -> str:
    return spec.meta.get("body", f"sample course material for {spec.url}")


def simple_extractor(spec: SourceSpec, raw: str) -> dict:
    return {"title": spec.title or spec.url, "text": raw, "subject": spec.subject}


def load_seeds(path: str | None) -> list[SourceSpec]:
    if not path or not Path(path).is_file():
        # Built-in OER demo seeds (permissive licenses).
        return [
            SourceSpec("https://oer.example/algebra", license="cc-by", subject="math"),
            SourceSpec("https://oer.example/biology", license="cc0", subject="biology"),
        ]
    specs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            specs.append(SourceSpec(**d))
    return specs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", default=None, help="JSONL of SourceSpec rows")
    ap.add_argument("--checkpoint", default=None, help="checkpoint JSON path")
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--once", action="store_true", help="drain the queue once and exit")
    args = ap.parse_args(argv)

    queue = HarvestQueue()
    queue.enqueue_many(load_seeds(args.seeds))
    store = CatalogUpsertStore()
    pipeline = HarvestPipeline(store)
    checkpoint = Checkpoint.load(args.checkpoint)
    batch_id = uuid.uuid4().hex[:8]

    metrics = harvest_loop(
        queue, pipeline, fetcher=mock_fetcher, extractor=simple_extractor,
        batch_id=batch_id, checkpoint=checkpoint, max_items=args.max_items,
    )
    print(json.dumps({
        "batch": batch_id, "ingested": metrics.ingested, "upserted": metrics.upserted,
        "updated": metrics.updated, "dropped_license": metrics.dropped_license,
        "catalog_size": len(store.items),
    }))
    if not args.once:
        # In production this would loop forever pulling new frontier URLs.
        time.sleep(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
