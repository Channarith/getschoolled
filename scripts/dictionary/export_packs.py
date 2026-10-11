#!/usr/bin/env python3
"""Shim → Theodore RAG lab export_packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.corpus_lab import export_packs

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ship", action="store_true")
    args = ap.parse_args(argv)
    print(json.dumps(export_packs(ship=args.ship), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
