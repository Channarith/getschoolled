#!/usr/bin/env python3
"""Shim → Theodore RAG lab route_review."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.corpus_lab import run_route_review

    print(json.dumps(run_route_review(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
