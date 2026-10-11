#!/usr/bin/env python3
"""Shim → Theodore RAG lab corpus train-update."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.cli_corpus import corpus_update_main

    return corpus_update_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
