#!/usr/bin/env python3
"""Shim → Theodore RAG lab baseline seed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.corpus_lab import seed_baselines

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-fixtures", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    print(json.dumps(seed_baselines(force=args.force or args.from_fixtures), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
