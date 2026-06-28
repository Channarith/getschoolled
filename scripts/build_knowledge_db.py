#!/usr/bin/env python3
"""Build/refresh the persistent embedded knowledge database (SQLite).

The DB is normally built automatically on first use; run this to pre-warm it or
to point it at a specific path via --out (or the AOEP_KNOWLEDGE_DB env var).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aoep_shared.training_agents.knowledge_store import KnowledgeStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the embedded knowledge DB")
    parser.add_argument("--out", default="", help="DB path (default: ~/.cache/aoep/knowledge.db)")
    args = parser.parse_args()

    store = KnowledgeStore(Path(args.out) if args.out else None)
    store.rebuild()
    status = store.status()
    print(f"backend={status['backend']} persistent={status['persistent']}")
    print(f"db_path={status['db_path']}")
    print(f"fts5={status['fts5']} count={status['count']} signature={status['signature']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
