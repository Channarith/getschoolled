#!/usr/bin/env python3
"""Dump the real safety knowledge base to JSON (for transparency / inspection)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from aoep_shared.training_agents.knowledge_base import (
    all_facts,
    fact_to_dict,
    knowledge_meta,
    knowledge_sources,
)


def main() -> int:
    out = Path(__file__).resolve().parent.parent / (
        "packages/shared/src/aoep_shared/training_agents/data/knowledge_base.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = knowledge_meta()
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": meta["count"],
        "sources": knowledge_sources(),
        "categories": meta["categories"],
        "facts": [fact_to_dict(f) for f in all_facts()],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {meta['count']} real cited facts from {meta['sources']} authorities")
    for s in knowledge_sources():
        print(f"  {s['source']}: {s['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
