"""Shared shim helpers: prefer Theodore RAG lab modules, fall back to local paths."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def ensure_paths() -> None:
    for p in (
        _REPO / "subrepos" / "theodore_rag_lab" / "src",
        _REPO / "packages" / "shared" / "src",
    ):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
